/* =========================================================================
 * This file is part of sys-c++ 
 * =========================================================================
 * 
 * (C) Copyright 2004 - 2009, General Dynamics - Advanced Information Systems
 *
 * sys-c++ is free software; you can redistribute it and/or modify
 * it under the terms of the GNU Lesser General Public License as published by
 * the Free Software Foundation; either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public 
 * License along with this program; If not, 
 * see <http://www.gnu.org/licenses/>.
 *
 */


#if defined(WIN32) && defined(_REENTRANT)

#if !defined(USE_NSPR_THREADS) && !defined(__POSIX)

#include "sys/SemaphoreWin32.h"

sys::SemaphoreWin32::SemaphoreWin32(unsigned int count)
{
    mNative = CreateSemaphore(NULL, count, MAX_COUNT, NULL);
    if (mNative == NULL)
        throw sys::SystemException("CreateSempaphore Failed");

}

void sys::SemaphoreWin32::wait()
{
    DWORD waitResult = WaitForSingleObject(
                           mNative,
                           INFINITE);
    if (waitResult != WAIT_OBJECT_0)
    {
        throw sys::SystemException("Semaphore wait failed");
    }
}

void sys::SemaphoreWin32::signal()
{
    if (!ReleaseSemaphore(mNative,
                          1,
                          NULL) )
    {
        throw sys::SystemException("Semaphore signal failed");
    }
}

HANDLE& sys::SemaphoreWin32::getNative()
{
    return mNative;
}

#endif
#endif
